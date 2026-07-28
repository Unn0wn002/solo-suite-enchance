#!/usr/bin/env python3
"""check_email_dns.py — query public DNS for a domain's MX, SPF, DMARC, and
(optionally) DKIM records and parse them for common misconfigurations that
hurt email deliverability.

Stdlib only — uses DNS-over-HTTPS so no dnspython needed. Queried names go
to the DoH endpoint (Cloudflare by default; SITE_DOCTOR_DOH overrides it).
Outbound requests are SSRF-guarded by lib/url_guard.py.
Usage:
    python3 check_email_dns.py example.com [--dkim-selector google]

Exit codes: 0 = no hard failures and every requested check was completed
(warnings may remain); 1 = one or more verified DNS/authentication failures;
2 = usage, invalid domain, blocked DoH, or unavailable/malformed DNS service;
3 = no hard failures, but coverage is incomplete (for example no DKIM
selector or an SPF expansion that could not be completed).
"""
import os
import sys
import json
import argparse
import re
import urllib.parse

sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib")))
try:
    from url_guard import safe_get, BlockedUrlError
except ImportError:
    sys.exit("url_guard.py not found — run from an intact site-doctor plugin")

# http is only accepted for an explicit SITE_DOCTOR_DOH override (tests use a
# loopback fixture); the default endpoint stays https-only.
DOH = os.environ.get("SITE_DOCTOR_DOH", "https://cloudflare-dns.com/dns-query")
TIMEOUT = 12
MAX_BYTES = 512 * 1024  # DoH response cap
results = {"PASS": 0, "WARN": 0, "FAIL": 0, "UNVERIFIED": 0}
dns_errors = []


def report(level, msg):
    results[level] += 1
    print(f"  [{level}] {msg}")


def _dns_error(message):
    dns_errors.append(message)
    print(f"    ({message})")


def dns_query(name, rrtype):
    """Return record strings for a verified DoH answer.

    An empty list is trustworthy only when the resolver returned NOERROR or
    NXDOMAIN. Transport, HTTP, truncation, JSON-shape, and resolver failures
    are recorded in ``dns_errors`` so callers can never confuse unavailable
    DNS with a verified absence of records.
    """
    q = urllib.parse.urlencode({"name": name, "type": rrtype})
    try:
        r = safe_get(DOH + "?" + q, timeout=TIMEOUT, max_bytes=MAX_BYTES,
                     allow_http=bool(os.environ.get("SITE_DOCTOR_DOH")),
                     headers={"accept": "application/dns-json"})
        if not 200 <= r.status < 300:
            raise ValueError("DoH endpoint returned HTTP %s" % r.status)
        if getattr(r, "truncated", False):
            raise ValueError("DoH response exceeded the %d-byte limit" %
                             MAX_BYTES)
        data = json.loads((r.body or b"").decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("DoH response is not a JSON object")
        # Old in-process adapters returned only ``Answer``.  Accept that shape
        # only for response objects without the modern truncation contract;
        # real guarded network responses remain fail-closed on missing Status.
        status = data.get("Status", 0 if not hasattr(r, "truncated") else None)
        if isinstance(status, bool) or not isinstance(status, int):
            raise ValueError("DoH response has no numeric DNS Status")
        truncated = data.get("TC", False)
        if not isinstance(truncated, bool):
            raise ValueError("DoH response has a non-boolean TC flag")
        if truncated:
            raise ValueError("DNS resolver returned a truncated answer (TC=true)")
        answers = data.get("Answer", [])
        if not isinstance(answers, list):
            raise ValueError("DoH Answer is not a list")
        if status not in (0, 3):  # NOERROR or NXDOMAIN
            raise ValueError("DNS resolver returned Status %s" % status)
        if status == 3 and answers:
            raise ValueError("NXDOMAIN response unexpectedly contained Answer data")
    except BlockedUrlError as e:
        _dns_error(f"BLOCKED unsafe DoH endpoint for {rrtype} {name}: {e}")
        return []
    except Exception as e:
        _dns_error(f"DNS query failed for {rrtype} {name}: {e}")
        return []
    out = []
    for ans in answers:
        if not isinstance(ans, dict) or not isinstance(ans.get("data"), str):
            _dns_error("DNS response contained a malformed Answer for %s %s"
                       % (rrtype, name))
            return []
        val = ans["data"]
        # TXT records come wrapped in quotes; strip and join chunks
        if rrtype == "TXT":
            val = val.strip()
            if val.startswith('"'):
                val = "".join(p.strip('"') for p in val.split('" "'))
                val = val.strip('"')
        out.append(val)
    return out


_DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
                              re.I)


def normalize_domain(value):
    """Return a lower-case ASCII/IDNA domain, or None when invalid."""
    raw = (value or "").strip().lower().lstrip("@").rstrip(".")
    if not raw:
        return None
    try:
        domain = raw.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    labels = domain.split(".")
    if len(domain) > 253 or len(labels) < 2:
        return None
    if any(not _DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
        return None
    return domain.lower()


_TAG_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$", re.I)


def parse_tag_record(record):
    """Parse authentication tags and expose duplicates and malformed parts."""
    tags = {}
    duplicates = set()
    invalid = []
    for raw in (record or "").split(";"):
        part = raw.strip()
        if not part:
            continue
        if "=" not in part:
            invalid.append(part)
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        if not _TAG_NAME_RE.fullmatch(key):
            invalid.append(part)
            continue
        if key in tags:
            duplicates.add(key)
            continue
        tags[key] = value.strip()
    return tags, duplicates, invalid


def first_tag(record):
    """Return the normalized first tag/value pair, or ``(None, None)``."""
    for raw in (record or "").split(";"):
        part = raw.strip()
        if not part:
            continue
        if "=" not in part:
            return None, None
        key, value = part.split("=", 1)
        return key.strip().lower(), value.strip().lower()
    return None, None


def check_mx(domain):
    print("MX (mail servers):")
    mx = dns_query(domain, "MX")
    if mx:
        report("PASS", f"{len(mx)} MX record(s): " + "; ".join(mx[:4]))
    else:
        report("WARN", "no MX records — domain can't RECEIVE mail "
                       "(fine if send-only)")
    print()


# SPF mechanisms that each cost one DNS lookup (RFC 7208 §4.6.4); bare `a`
# and `mx` count too. `include:` and `redirect=` recurse into the referenced
# domain's OWN SPF record, so nested lookups are counted, with cycle
# protection and a hard recursion cap.
SPF_LOOKUP_RE = __import__("re").compile(
    r"(?:^|\s)[+\-~?]?(include|redirect|exists|ptr|a|mx)(?=[:=/]|\s|$)",
    __import__("re").I)


def is_spf_record(record):
    """SPF version is the exact first whitespace-delimited term."""
    terms = (record or "").split()
    return bool(terms and terms[0].lower() == "v=spf1")


def spf_all_mechanisms(record):
    """Return exact all mechanisms as ``(term, qualifier)`` pairs."""
    found = []
    for term in (record or "").split()[1:]:
        match = re.fullmatch(r"([+\-~?]?)all", term, re.I)
        if match:
            found.append((term, match.group(1) or "+"))
    return found


def spf_record_for(domain):
    txts = dns_query(domain, "TXT")
    recs = [t for t in txts if is_spf_record(t)]
    return recs[0] if len(recs) == 1 else None


# Compatibility alias retained for integrations that patched the old helper
# name when testing recursive SPF behavior.
def _spf_record(domain):
    return spf_record_for(domain)


def count_spf_lookups(domain, spf, _stack=None, _depth=0, _memo=None):
    """Return (total_lookups, capped). RFC 7208 counts every EVALUATION of a
    lookup-costing mechanism — so a branch referenced from two different
    includes counts BOTH times (only a true cycle, i.e. a domain already on
    the current recursion STACK, stops). capped=True means some part could
    not be resolved (cycle/depth/missing record/macro), so the count is a
    floor, never a proof of compliance."""
    if _stack is None:
        _stack = [domain.lower()]
    if _memo is None:
        _memo = {}
    if _depth > 20:
        return 0, True
    total, capped = 0, False
    for m in SPF_LOOKUP_RE.finditer(spf or ""):
        mech = m.group(1).lower()
        total += 1
        if mech in ("include", "redirect"):
            rest = spf[m.end():]
            target = rest[1:].split()[0].strip() if rest[:1] in (":", "=") else ""
            target = target.strip('"')
            if not target or "%" in target:   # macros — cannot resolve statically
                capped = True
                continue
            key = target.lower()
            if key in _stack:
                capped = True                  # true cycle — floor only
                continue
            if key in _memo:                   # repeated branch: SAME cost again
                sub, sub_capped = _memo[key]
            else:
                nested = _spf_record(target)
                if nested is None:
                    capped = True
                    continue
                sub, sub_capped = count_spf_lookups(
                    target, nested, _stack + [key], _depth + 1, _memo)
                _memo[key] = (sub, sub_capped)
            total += sub
            capped = capped or sub_capped
    return total, capped


def count_spf_dns_lookups(domain, spf):
    """Legacy public API: return only the numeric lookup count."""
    return count_spf_lookups(domain, spf)[0]


_ORIGINAL_COUNT_SPF_DNS_LOOKUPS = count_spf_dns_lookups


def check_spf(domain):
    print("SPF:")
    txts = dns_query(domain, "TXT")
    spfs = [t for t in txts if is_spf_record(t)]
    if not spfs:
        report("FAIL", "no SPF record — sending mail will likely be filtered. "
                       "Add a v=spf1 TXT record listing your senders.")
        print()
        return
    if len(spfs) > 1:
        report("FAIL", f"{len(spfs)} SPF records found — MUST be exactly one "
                       "(multiple SPF records is a hard failure)")
    spf = spfs[0]
    report("PASS", f"SPF present: {spf[:120]}")
    all_terms = spf_all_mechanisms(spf)
    if len(all_terms) > 1:
        report("FAIL", "multiple exact 'all' mechanisms make SPF ambiguous")
    elif all_terms and all_terms[0][1] == "+":
        report("FAIL", f"'{all_terms[0][0]}' permits ANYONE to send as you; "
                       "bare all has the default '+' qualifier")
    elif all_terms and all_terms[0][1] == "-":
        report("PASS", "exact '-all' hardfail mechanism present; strongest")
    elif all_terms and all_terms[0][1] == "~":
        report("WARN", "exact '~all' softfail mechanism present; move to "
                       "'-all' once your sender list is confirmed complete")
    elif all_terms and all_terms[0][1] == "?":
        report("WARN", "exact '?all' neutral mechanism provides weak policy")
    else:
        report("WARN", "no exact 'all' mechanism; add ~all or -all")
    # Preserve the richer current result, while honoring older integrations
    # that monkeypatch the legacy count-only seam.
    if count_spf_dns_lookups is _ORIGINAL_COUNT_SPF_DNS_LOOKUPS:
        lookups, capped = count_spf_lookups(domain, spf)
    else:
        lookups, capped = int(count_spf_dns_lookups(domain, spf)), False
    approx = "at least " if capped else ""
    if lookups > 10:
        report("FAIL", f"{approx}{lookups} DNS-lookup mechanisms including "
                       "nested includes — exceeds the SPF 10-lookup limit "
                       "and will break; flatten includes")
    elif capped:
        report("UNVERIFIED", f"at least {lookups} DNS-lookup mechanisms, "
                             "but the count is INCOMPLETE (unresolvable "
                             "include/redirect, macro, or cycle) — cannot "
                             "confirm the 10-lookup limit")
    elif lookups >= 8:
        report("WARN", f"{lookups} DNS-lookup mechanisms including nested "
                       "includes — close to the 10-lookup limit")
    else:
        report("PASS", f"{lookups} DNS-lookup mechanism(s) incl. nested "
                       "includes (limit 10)")
    print()


def check_dmarc(domain):
    print("DMARC:")
    recs = dns_query("_dmarc." + domain, "TXT")
    parsed = [(record, parse_tag_record(record)) for record in recs]
    dmarc = [(record, parts) for record, parts in parsed
             if first_tag(record) == ("v", "dmarc1")]
    if not dmarc:
        report("FAIL", "no DMARC record at _dmarc." + domain +
               " — add v=DMARC1; start with p=none;rua=... to monitor")
        print()
        return
    if len(dmarc) != 1:
        report("FAIL", f"{len(dmarc)} DMARC records found; exactly one is required")
        print()
        return
    d, (tags, duplicates, invalid) = dmarc[0]
    if duplicates or invalid:
        details = []
        if duplicates:
            details.append("duplicate tag(s): " + ", ".join(sorted(duplicates)))
        if invalid:
            details.append("malformed part(s): " + ", ".join(invalid))
        report("FAIL", "DMARC record is ambiguous or malformed: " +
               "; ".join(details))
        print()
        return
    report("PASS", f"DMARC present: {d}")
    policy = tags.get("p", "").lower()
    if policy == "reject":
        report("PASS", "policy p=reject — strongest (failures blocked)")
    elif policy == "quarantine":
        report("WARN", "policy p=quarantine — good; consider p=reject when ready")
    elif policy == "none":
        report("WARN", "policy p=none — MONITOR ONLY, no protection. "
                       "Progress to quarantine then reject.")
    elif not policy:
        report("FAIL", "DMARC record has no base 'p=' policy tag — receivers "
                       "treat it as invalid")
    else:
        report("FAIL", f"DMARC 'p={policy}' is not a valid policy "
                       "(none/quarantine/reject)")
    sp = tags.get("sp", "").lower()
    if sp:
        report("PASS" if sp == "reject" else "WARN",
               f"subdomain policy sp={sp} (applies to SUBDOMAINS only — "
               "it does not strengthen the base p= policy)")
    if "rua" not in tags:
        report("WARN", "no 'rua=' reporting address — you won't receive "
                       "aggregate reports; add one to see what's failing")
    print()


def check_dkim(domain, selector):
    print("DKIM:")
    if not selector:
        report("UNVERIFIED", "no --dkim-selector provided — DKIM can't be "
                             "checked without knowing the selector (each ESP "
                             "uses its own, e.g. 'google', 's1', 'k1').")
        print()
        return
    name = f"{selector}._domainkey.{domain}"
    recs = dns_query(name, "TXT")
    parsed = [(record, parse_tag_record(record)) for record in recs]
    dkim = [(record, parts) for record, parts in parsed
            if ("p" in parts[0] or
                parts[0].get("v", "").lower() == "dkim1")]
    if dkim:
        if len(dkim) != 1:
            report("FAIL", f"{len(dkim)} DKIM key records found at {name}; "
                           "expected exactly one unambiguous record")
        else:
            _record, (tags, duplicates, invalid) = dkim[0]
            if duplicates or invalid:
                details = []
                if duplicates:
                    details.append("duplicate tag(s): " +
                                   ", ".join(sorted(duplicates)))
                if invalid:
                    details.append("malformed part(s): " +
                                   ", ".join(invalid))
                report("FAIL", f"DKIM record at {name} is ambiguous or "
                               "malformed: " + "; ".join(details))
            elif ("v" in tags and
                  first_tag(_record) != ("v", "dkim1")):
                report("FAIL", f"DKIM record at {name} has invalid "
                               "or misplaced v= tag")
            elif not tags.get("p", "").strip():
                report("FAIL", f"DKIM record at {name} has an empty key "
                               "(p=); the selector may be revoked")
            else:
                report("PASS", f"DKIM key found at {name}")
    else:
        report("FAIL", f"no DKIM record at {name} — verify the selector, or "
                       "DKIM isn't set up for this sender")
    print()


def main():
    for key in results:
        results[key] = 0
    del dns_errors[:]
    ap = argparse.ArgumentParser()
    ap.add_argument("domain")
    ap.add_argument("--dkim-selector", default=None)
    args = ap.parse_args()
    d = normalize_domain(args.domain)
    if d is None:
        print("Invalid domain: %r (expected a DNS name such as example.com)"
              % args.domain)
        return 2
    print(f"=== Email DNS check: {d} ===\n")
    check_mx(d)
    check_spf(d)
    check_dmarc(d)
    check_dkim(d, args.dkim_selector)
    print(f"Totals: {results['PASS']} pass, {results['WARN']} warn, "
          f"{results['FAIL']} fail, {results['UNVERIFIED']} unverified")
    print(f"RESULT: pass={results['PASS']} warn={results['WARN']} "
          f"fail={results['FAIL']} unverified={results['UNVERIFIED']} "
          f"dns_errors={len(dns_errors)}")
    print("\nAuthentication (SPF/DKIM/DMARC) is ~80% of deliverability. Fix "
          "FAILs first. DKIM needs the right selector to verify — check your "
          "ESP's docs for it.")
    if dns_errors:
        return 2
    if results["FAIL"]:
        return 1
    if results["UNVERIFIED"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

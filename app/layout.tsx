import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Solo Suite Enchance — The developer operating system",
  description:
    "Solo Suite Enchance is the larger-project developer operating system for Claude, Codex, and Antigravity.",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  openGraph: {
    title: "Solo Suite Enchance — The developer operating system",
    description:
      "Solo Suite Enchance is the larger-project developer operating system for Claude, Codex, and Antigravity.",
    images: [{ url: "/og.png", width: 1536, height: 1024, alt: "Solo Suite Enchance — Ship like a company. Think like a solo." }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Solo Suite Enchance — The developer operating system",
    description:
      "Solo Suite Enchance is the larger-project developer operating system for Claude, Codex, and Antigravity.",
    images: ["/og.png"],
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        {children}
      </body>
    </html>
  );
}

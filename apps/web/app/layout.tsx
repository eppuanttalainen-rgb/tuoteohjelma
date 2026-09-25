import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Machine Compliance Intelligence",
  description: "Evidence-first machine reconstruction for brownfield retrofit projects.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

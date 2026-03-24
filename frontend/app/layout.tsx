import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/layout/nav";

export const metadata: Metadata = {
  title: "XAU/USD Trader",
  description: "AI-assisted gold trading dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-bg text-foreground antialiased">
        <Nav />
        <main className="w-full px-4 py-4">{children}</main>
      </body>
    </html>
  );
}

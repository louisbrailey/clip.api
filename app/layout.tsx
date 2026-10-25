import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Constellation · Creative Operations",
  description: "Your private control room for creative teams, authorized publishing and Astra-led delegation.",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/clip-api-logo.png",
    shortcut: "/clip-api-logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}

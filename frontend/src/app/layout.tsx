import type { Metadata } from "next";
import "@/styles/globals.css";
import { AuthProvider } from "@/providers/AuthProvider";

export const metadata: Metadata = {
  title: "TablePulse — Restaurant Floor Intelligence",
  description:
    "Open-source, privacy-first restaurant floor operations and table-turnover platform.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}

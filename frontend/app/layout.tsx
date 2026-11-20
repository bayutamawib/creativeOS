import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
export const metadata: Metadata = {
  title: "Creative OS",
  description: "Creative agency workspace",
};
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="bg-white border-b border-border px-6 py-5 sm:px-12">
          <div className="mx-auto max-w-6xl font-bold tracking-tight text-xl">
            Creative <span className="text-primary">OS</span>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}

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
        <header className="border-b border-border bg-white px-4 py-5 sm:px-6 lg:px-8">
          <div className="text-xl font-bold tracking-tight">
            Creative <span className="text-primary">OS</span>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}

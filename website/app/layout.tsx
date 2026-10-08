import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Provider } from "@/components/provider";
import { site } from "@/lib/site";
import "./global.css";

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: {
    default: "ohkit — Agent harnesses, a Python interface",
    template: "%s | ohkit",
  },
  description: site.description,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}

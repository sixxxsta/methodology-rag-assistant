import type { Metadata } from "next";
import { DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-dm-sans",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin", "cyrillic"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "Методолог — RAG-ассистент",
  description: "Карманный ментор по Agile, Scrum, DevOps и проектной методологии",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={`${dmSans.variable} ${jetbrains.variable} h-full`}>
      <body className="h-full font-sans">{children}</body>
    </html>
  );
}

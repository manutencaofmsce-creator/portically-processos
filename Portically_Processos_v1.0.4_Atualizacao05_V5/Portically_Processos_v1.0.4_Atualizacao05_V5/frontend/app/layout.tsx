import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Portically Processos",
  description: "Módulo privado de acompanhamento processual do Portically Hub",
  robots: {
    index: false,
    follow: false
  }
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}

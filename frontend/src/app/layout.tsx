import type { Metadata } from "next";
import { AuthProvider } from "@/components/auth";
import "./globals.css";
export const metadata: Metadata = {
  title: { default: "EvalRAG · Research console", template: "%s · EvalRAG" },
  description:
    "Grounded answers, inspectable retrieval and reproducible AI evaluations.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}

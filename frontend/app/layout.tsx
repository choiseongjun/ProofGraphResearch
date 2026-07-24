import "./globals.css";

export const metadata = { title: "ProofGraph 워크플로 AI", description: "근거 중심 워크플로 기반 AI 시스템" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}

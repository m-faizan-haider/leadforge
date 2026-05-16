import type { Metadata } from 'next';
import './globals.css';
import Link from 'next/link';
import AuthNav from '@/components/AuthNav';

export const metadata: Metadata = {
  title: 'LeadForge AI SaaS',
  description: 'AI-Powered Local Business Prospecting Engine',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="container">
          <header className="header">
            <Link href="/" style={{ textDecoration: 'none' }}>
              <h1>LeadForge AI</h1>
            </Link>
            <AuthNav />
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}

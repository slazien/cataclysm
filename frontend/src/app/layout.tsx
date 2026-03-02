import type { Metadata } from 'next';
import { Providers } from '@/components/Providers';
import { NetworkStatus } from '@/components/shared/NetworkStatus';
import './globals.css';

export const metadata: Metadata = {
  title: 'Cataclysm — AI Track Coaching',
  description: 'Post-session telemetry analysis and AI coaching for HPDE drivers',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased">
        <Providers>
          <NetworkStatus />
          {children}
        </Providers>
      </body>
    </html>
  );
}

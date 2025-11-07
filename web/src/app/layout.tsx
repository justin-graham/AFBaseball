import './globals.css';
import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AF Baseball Analytics Hub',
  description: 'Leaderboards, charts, scouting intel — powered by Supabase and Google Sheets.',
};

const links = [
  { href: '/', label: 'Landing' },
  { href: '/pitching', label: 'Pitching' },
  { href: '/hitting', label: 'Hitting' },
  { href: '/catching', label: 'Catching' },
  { href: '/scouting', label: 'Scouting' },
  { href: '/umpires', label: 'Umpires' },
  { href: '/video', label: 'Video' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head></head>
      <body>
        <header>
          <Link className="brand" href="/">
            AF Baseball Analytics
          </Link>
          <nav>
            {links.map((link) => (
              <Link key={link.href} href={link.href}>
                {link.label}
              </Link>
            ))}
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}

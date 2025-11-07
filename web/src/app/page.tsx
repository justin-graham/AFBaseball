'use client';

import Link from 'next/link';
import { useMemo } from 'react';

const videos = ['/videos/AFBBV1.mov', '/videos/AFBBV2.mov', '/videos/AFBBV3.mov'];
const cards = [
  { name: 'Pitching', href: '/pitching' },
  { name: 'Hitting', href: '/hitting' },
  { name: 'Catching', href: '/catching' },
  { name: 'Scouting', href: '/scouting' },
  { name: 'Umpires', href: '/umpires' },
  { name: 'Video', href: '/video' },
];

export default function HomePage() {
  const video = useMemo(() => videos[Math.floor(Math.random() * videos.length)], []);

  return (
    <main style={{ padding: 0, maxWidth: 'none' }}>
      <video autoPlay loop muted playsInline style={{ width: '100vw', display: 'block' }}>
        <source src={video} />
      </video>
      <div style={{ maxWidth: '1080px', margin: '0 auto', padding: '48px 28px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px', justifyContent: 'center' }}>
          {cards.map((card) => (
            <Link
              key={card.href}
              href={card.href}
              className="panel"
              style={{ textAlign: 'center', flex: '1 1 calc(33.333% - 12px)', minWidth: '240px', maxWidth: '340px' }}
            >
              <h2>{card.name}</h2>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}

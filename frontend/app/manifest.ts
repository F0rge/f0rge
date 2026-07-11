import type { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Marrow',
    short_name: 'Marrow',
    description: 'Daily symptom check-in and health tracking.',
    start_url: '/checkin',
    display: 'standalone',
    theme_color: '#131110',
    background_color: '#F4EEE6',
    icons: [
      {
        src: '/icons/icon-192.png',
        sizes: '192x192',
        type: 'image/png',
      },
      {
        src: '/icons/icon-512.png',
        sizes: '512x512',
        type: 'image/png',
      },
    ],
  }
}

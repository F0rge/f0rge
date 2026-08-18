import type { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Marrow',
    short_name: 'Marrow',
    description: 'Daily symptom check-in and health tracking.',
    start_url: '/checkin',
    display: 'standalone',
    theme_color: '#000000',
    background_color: '#F2F1EF',
    icons: [
      {
        src: '/icons/icon-32.png',
        sizes: '32x32',
        type: 'image/png',
      },
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

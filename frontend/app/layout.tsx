import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import { Toaster } from 'sonner'
import { Providers } from '@/components/providers'
import { BottomNav } from '@/components/bottom-nav'
import './globals.css'

const inter = Inter({
  variable: '--font-sans',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'Marrow',
  description: 'Daily symptom check-in and health tracking.',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Marrow',
  },
  openGraph: {
    title: 'Marrow',
    description: 'Daily symptom check-in and health tracking.',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'Marrow' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Marrow',
    description: 'Daily symptom check-in and health tracking.',
    images: ['/og-image.png'],
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#F4EEE6' },
    { media: '(prefers-color-scheme: dark)', color: '#131110' },
  ],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col font-sans">
        <Providers>
          <div className="flex-1 pb-[calc(84px+env(safe-area-inset-bottom))]">{children}</div>
          <BottomNav />
          <Toaster position="top-center" richColors />
        </Providers>
      </body>
    </html>
  )
}

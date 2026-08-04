import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import { Toaster } from 'sonner'
import { AppShell } from '@/components/layout/app-shell'
import { Providers } from '@/components/providers'
import './globals.css'

const inter = Inter({
  variable: '--font-sans',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'Marrow',
  description: 'Daily symptom check-in and health tracking.',
  // ICO + PNG only — SVG favicons break on dark browser chrome (Clay stroke invisible).
  icons: {
    icon: [{ url: '/favicon.ico', sizes: 'any' }],
    shortcut: '/favicon.ico',
    apple: '/apple-icon.png',
  },
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
          <AppShell>{children}</AppShell>
          <Toaster position="top-center" richColors />
        </Providers>
      </body>
    </html>
  )
}

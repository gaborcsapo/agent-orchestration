import './globals.css'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Privacy-Preserving Negotiation Arena',
  description: 'Multi-agent negotiation with privacy through physical separation',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}

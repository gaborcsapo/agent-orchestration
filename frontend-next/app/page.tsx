'use client'

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export default function Home() {
  const router = useRouter()

  useEffect(() => {
    router.push('/arena')
  }, [router])

  return (
    <div className="page-container">
      <div className="empty-state">
        <div className="spinner" />
        <p>Redirecting to Arena...</p>
      </div>
    </div>
  )
}

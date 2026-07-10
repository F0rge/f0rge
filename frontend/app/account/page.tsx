'use client'

import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import { ProfileSection } from '@/components/account/profile-section'
import { PasswordSection } from '@/components/account/password-section'
import { ExportDataSection } from '@/components/account/export-data-section'
import { LogoutSection } from '@/components/account/logout-section'
import { DeleteAccountSection } from '@/components/account/delete-account-section'

export default function AccountPage() {
  return (
    <PageShell className="py-2">
      <PageHeader
        className="mb-6"
        title={
          <div className="flex items-center gap-3">
            <Link href="/settings" className="text-muted-foreground hover:text-foreground">
              <ArrowLeft className="size-5" />
            </Link>
            <h1 className="text-xl font-bold">Account</h1>
          </div>
        }
      />

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-6">
          <ProfileSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <PasswordSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <ExportDataSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <LogoutSection />
        </div>
        <div className="col-span-12">
          <DeleteAccountSection />
        </div>
      </div>
    </PageShell>
  )
}

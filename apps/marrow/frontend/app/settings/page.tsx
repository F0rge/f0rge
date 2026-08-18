'use client'

import { useState, type ReactNode } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  ArrowLeft, Cloud, Database, Eye, EyeOff, GraduationCap, Heart, Lock, LogOut, Search,
  SlidersHorizontal, Sparkles, SunMoon, Tag, UserPlus, UserRound, UsersRound,
  UtensilsCrossed, type LucideIcon,
} from 'lucide-react'
import { Input } from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import { ThemeToggle } from '@/components/layout/theme-toggle'
import { IconWell } from '@/components/shared/color-artifact'
import { SettingsLinkRow } from '@/components/settings/settings-link-row'
import { SettingsAccordionRow } from '@/components/settings/settings-accordion-row'
import { WeatherSection } from '@/components/settings/weather-section'
import { AiSettingsSection } from '@/components/settings/ai-settings-section'
import { ExternalTokenSection } from '@/components/settings/external-token-section'
import { AppleHealthSection } from '@/components/settings/apple-health-section'
import { DataSourcesSection } from '@/components/settings/data-sources-section'
import { OnboardingSection } from '@/components/settings/onboarding-section'
import { TaggedMealsSection } from '@/components/settings/tagged-meals-section'
import { ProfileVisibilitySection } from '@/components/settings/profile-visibility-section'
import { HiddenMealsSection } from '@/components/settings/hidden-meals-section'
import { useConnections, useGroups, useLogout, useMealTags } from '@/lib/api/hooks'

interface RowEntry {
  title: string
  description?: string
  node: ReactNode
}

interface GroupEntry {
  title: string
  rows: RowEntry[]
}

function link(title: string, description: string, href: string, Icon: LucideIcon, badge = 0): RowEntry {
  return {
    title,
    description,
    node: (
      <SettingsLinkRow
        key={title}
        href={href}
        icon={<Icon className="size-4" />}
        title={title}
        description={description}
        badge={badge}
      />
    ),
  }
}

function accordion(title: string, description: string, Icon: LucideIcon, content: ReactNode): RowEntry {
  return {
    title,
    description,
    node: (
      <SettingsAccordionRow key={title} icon={<Icon className="size-4" />} title={title} description={description}>
        {content}
      </SettingsAccordionRow>
    ),
  }
}

export default function SettingsPage() {
  const router = useRouter()
  const logout = useLogout()
  const [query, setQuery] = useState('')
  const pendingConnections = useConnections().data?.pending_incoming.length ?? 0
  const pendingInvites = useGroups().data?.filter((g) => g.my_status === 'invited').length ?? 0
  const pendingTags = useMealTags().data?.incoming_pending.length ?? 0

  const handleLogout = async () => {
    try {
      await logout.mutateAsync()
      router.replace('/login')
    } catch (err) {
      handleMutationError(err, 'Could not log out')
    }
  }

  const allGroups: GroupEntry[] = [
    {
      title: 'Your account',
      rows: [
        link('Account', 'Profile, password, data export', '/account', UserRound),
        link('Customize', 'Check-in cards, symptoms, diet tags', '/customize', SlidersHorizontal),
      ],
    },
    {
      title: 'Your connections',
      rows: [
        link('Connections', 'Requests and people you can tag on meals', '/people/connections', UserPlus, pendingConnections),
        link('Groups', 'Organize connected people into named groups', '/people/groups', UsersRound, pendingInvites),
        link('Tagged meals', 'Meal tags waiting for your approval', '/people/tags', Tag, pendingTags),
      ],
    },
    {
      title: 'How you use Marrow',
      rows: [
        {
          title: 'Appearance',
          description: 'Theme for this device',
          node: (
            <div key="Appearance" className="flex items-center gap-3 px-4 py-3.5">
              <IconWell>
                <SunMoon className="size-4" />
              </IconWell>
              <div className="min-w-0 flex-1">
                <span className="text-sm font-medium">Appearance</span>
                <p className="mt-0.5 text-xs leading-snug text-muted-foreground">Theme for this device</p>
              </div>
              <div className="-my-2 -mr-3 w-40 shrink-0">
                <ThemeToggle />
              </div>
            </div>
          ),
        },
        accordion('Onboarding', 'Replay the guided app tour', GraduationCap, <OnboardingSection />),
      ],
    },
    {
      title: 'Integrations',
      rows: [
        accordion('Weather', 'Local weather data for your check-ins', Cloud, <WeatherSection />),
        accordion('Apple Health', 'Sync health metrics from your iPhone', Heart, <AppleHealthSection />),
        accordion('External access token', 'API access for external tools', Lock, <ExternalTokenSection />),
      ],
    },
    {
      title: 'AI',
      rows: [accordion('AI settings', 'Chat and embedding model configuration', Sparkles, <AiSettingsSection />)],
    },
    {
      title: 'Social',
      rows: [
        accordion('Tagged meals defaults', 'Approve tags manually or add them automatically', UtensilsCrossed, <TaggedMealsSection />),
        accordion('Profile visibility', 'Auto-hide meals from your profile by diet tag', Eye, <ProfileVisibilitySection />),
        accordion('Hidden meals', 'Meals you removed from your profile grids', EyeOff, <HiddenMealsSection />),
      ],
    },
    {
      title: 'About',
      rows: [accordion('Data sources', 'Where catalog and reference data comes from', Database, <DataSourcesSection />)],
    },
    {
      title: 'Session',
      rows: [
        {
          title: 'Log out',
          node: (
            <button
              key="Log out"
              type="button"
              onClick={handleLogout}
              disabled={logout.isPending}
              className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/50 active:bg-muted disabled:opacity-50"
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                <LogOut className="size-4 text-destructive" />
              </span>
              <span className="flex-1 text-sm font-medium text-destructive">Log out</span>
            </button>
          ),
        },
      ],
    },
  ]

  const q = query.trim().toLowerCase()
  const visibleGroups = allGroups
    .map((group) => ({
      ...group,
      rows: group.rows.filter((row) => `${row.title} ${row.description ?? ''}`.toLowerCase().includes(q)),
    }))
    .filter((group) => group.rows.length > 0)

  return (
    <PageShell className="max-w-2xl space-y-6 pb-2">
      <PageHeader
        data-tour="settings-page"
        title={
          <div className="flex items-center gap-3">
            <Link href="/profile" className="text-muted-foreground hover:text-foreground" aria-label="Back to profile">
              <ArrowLeft className="size-5" />
            </Link>
            <h1 className="text-xl font-bold">Settings and activity</h1>
          </div>
        }
      />

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search settings"
          aria-label="Search settings"
          className="h-10 rounded-xl border-none bg-muted pl-9 dark:bg-muted"
        />
      </div>

      {visibleGroups.map((group) => (
        <section key={group.title} className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{group.title}</h2>
          <div className="divide-y divide-muted overflow-hidden rounded-xl border border-border">
            {group.rows.map((row) => row.node)}
          </div>
        </section>
      ))}

      {visibleGroups.length === 0 && (
        <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          No settings match your search.
        </p>
      )}
    </PageShell>
  )
}

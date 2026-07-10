/**
 * Onboarding tour step definitions — single source of truth.
 *
 * MAINTENANCE: When adding, removing, or renaming bottom-nav items, check-in
 * cards, customize hub tiles, or primary empty-state pages, update the steps
 * below AND the matching `data-tour` anchors in the referenced components.
 * Replay entry point: Settings → Help → Replay app tour.
 */

export interface TourStepDefinition {
  id: string
  route: string
  target: string
  title: string
  content: string
  placement?: 'top' | 'bottom' | 'left' | 'right' | 'center' | 'auto'
  isFixed?: boolean
}

export const TOUR_STEPS: TourStepDefinition[] = [
  {
    id: 'welcome',
    route: '/checkin',
    target: 'body',
    title: 'Welcome to Health Tracker',
    content:
      'This quick tour shows how to log daily symptoms, navigate the app, and unlock insights over time.',
    placement: 'center',
  },
  {
    id: 'bottom-nav',
    route: '/checkin',
    target: '[data-tour="bottom-nav"]',
    title: 'Main navigation',
    content:
      'Six tabs at the bottom: Today, History, Treatments, Labs, Insights, and Settings. You will visit each in this tour.',
    placement: 'top',
    isFixed: true,
  },
  {
    id: 'wellbeing',
    route: '/checkin',
    target: '[data-tour="checkin-wellbeing"]',
    title: 'Wellbeing scales',
    content:
      'Rate overall wellbeing, sleep, stress, and neurological symptoms. Tap a segment to set today\'s value.',
    placement: 'bottom',
  },
  {
    id: 'gut',
    route: '/checkin',
    target: '[data-tour="checkin-gut"]',
    title: 'Gut health',
    content:
      'Track bloating, stool status, Bristol type, and related gut symptoms on the same daily entry.',
    placement: 'bottom',
  },
  {
    id: 'food',
    route: '/checkin',
    target: '[data-tour="checkin-food"]',
    title: 'Food & diet',
    content:
      'Snap meal photos for AI analysis or log manually. Diet-risk tags flag high-histamine, FODMAP, gluten, and dairy items.',
    placement: 'bottom',
  },
  {
    id: 'supplements',
    route: '/checkin',
    target: '[data-tour="checkin-supplements"]',
    title: 'Supplements & medications',
    content:
      'Tap pills to mark what you took today. Your starter catalog is pre-seeded — customize active items in Customize.',
    placement: 'bottom',
  },
  {
    id: 'symptoms',
    route: '/checkin',
    target: '[data-tour="checkin-symptoms"]',
    title: 'Symptoms & trackers',
    content:
      'Log symptom severity and lifestyle trackers (caffeine, alcohol, etc.). Add your own in Customize when you are ready.',
    placement: 'bottom',
  },
  {
    id: 'autosave',
    route: '/checkin',
    target: '[data-tour="checkin-header"]',
    title: 'Autosave',
    content:
      'Edits save automatically as you go. A status capsule appears at the top when you scroll past the header.',
    placement: 'bottom',
  },
  {
    id: 'profile',
    route: '/checkin',
    target: '[data-tour="profile-menu"]',
    title: 'Profile menu',
    content:
      'Open your avatar for Account settings and Customize — where you reorder cards, edit catalogs, and add custom trackers.',
    placement: 'bottom',
    isFixed: true,
  },
  {
    id: 'customize',
    route: '/customize',
    target: '[data-tour="customize-hub"]',
    title: 'Customize hub',
    content:
      'Structural changes live here, not on the daily check-in. Reorder sections, manage catalogs, and add custom symptoms or trackers.',
    placement: 'bottom',
  },
  {
    id: 'history',
    route: '/history',
    target: '[data-tour="history-calendar"]',
    title: 'History',
    content:
      'Browse past months. Days with check-ins show a dot — tap a day to view or create an entry.',
    placement: 'bottom',
  },
  {
    id: 'treatments',
    route: '/treatments',
    target: '[data-tour="treatments-page"]',
    title: 'Treatments',
    content:
      'Track antibiotic courses, antimicrobials, and other protocols. Add a treatment when you start one.',
    placement: 'bottom',
  },
  {
    id: 'labs',
    route: '/labs',
    target: '[data-tour="labs-page"]',
    title: 'Labs',
    content:
      'Upload a lab PDF or photo for extraction, or add results manually. Trends appear here once you have data.',
    placement: 'bottom',
  },
  {
    id: 'insights',
    route: '/insights',
    target: '[data-tour="insights-header"]',
    title: 'Insights',
    content:
      'Trends and correlations unlock after you build a few weeks of check-ins. Adjust the date range and outcome above.',
    placement: 'bottom',
  },
  {
    id: 'settings',
    route: '/settings',
    target: '[data-tour="settings-page"]',
    title: 'Settings',
    content:
      'Connect weather, Apple Health, and optional AI keys. External API tokens for integrations also live here.',
    placement: 'bottom',
  },
  {
    id: 'done',
    route: '/checkin',
    target: '[data-tour="bottom-nav"]',
    title: 'You are all set',
    content:
      'Start today\'s check-in whenever you are ready. Replay this tour anytime from Settings → Help.',
    placement: 'top',
    isFixed: true,
  },
]

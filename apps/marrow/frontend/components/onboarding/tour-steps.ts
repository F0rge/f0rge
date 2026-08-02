/**
 * Onboarding tour step definitions — single source of truth.
 *
 * MAINTENANCE: When adding, removing, or renaming bottom-nav items, check-in
 * cards, customize hub tiles, or primary empty-state pages, update the steps
 * below AND the matching `data-tour` anchors in the referenced components.
 * Replay entry point: Settings → Help → Replay app tour.
 */

export type SetupKind = 'symptoms' | 'medications' | 'supplements' | 'trackers'

export interface TourStepDefinition {
  id: string
  route: string
  target: string
  title: string
  content: string
  placement?: 'top' | 'bottom' | 'left' | 'right' | 'center' | 'auto'
  isFixed?: boolean
  stepType?: 'setup' | 'tour'
  setupKind?: SetupKind
}

export const TOUR_STEPS: TourStepDefinition[] = [
  {
    id: 'welcome',
    route: '/checkin',
    target: 'body',
    title: 'Welcome to Marrow',
    content:
      'This quick tour shows how to log daily symptoms, navigate the app, and unlock insights over time.',
    placement: 'center',
    isFixed: true,
  },
  {
    id: 'setup-symptoms',
    route: '/checkin',
    target: 'body',
    title: 'Symptoms to track',
    content:
      'Pick symptoms for your daily check-in — tap quick picks or search our list. Choose as many or as few as you like.',
    placement: 'center',
    isFixed: true,
    stepType: 'setup',
    setupKind: 'symptoms',
  },
  {
    id: 'setup-medications',
    route: '/checkin',
    target: 'body',
    title: 'Common medications',
    content:
      'Search or pick medications you might log as needed. These become quick-add chips on your check-in.',
    placement: 'center',
    isFixed: true,
    stepType: 'setup',
    setupKind: 'medications',
  },
  {
    id: 'setup-supplements',
    route: '/checkin',
    target: 'body',
    title: 'Supplements you take',
    content:
      'Search or select supplements you want to track daily. Skip anything you do not use.',
    placement: 'center',
    isFixed: true,
    stepType: 'setup',
    setupKind: 'supplements',
  },
  {
    id: 'setup-trackers',
    route: '/checkin',
    target: 'body',
    title: 'Daily trackers',
    content:
      'Search or choose lifestyle trackers like water, exercise, or caffeine. We save your picks when you continue.',
    placement: 'center',
    isFixed: true,
    stepType: 'setup',
    setupKind: 'trackers',
  },
  {
    id: 'bottom-nav',
    route: '/checkin',
    target: '[data-tour="bottom-nav"]',
    title: 'Main navigation',
    content:
      'Six tabs at the bottom: Today, History, Treatments, Labs, Signals, and Profile. You will visit each in this tour.',
    placement: 'top',
    isFixed: true,
  },
  {
    id: 'wellbeing',
    route: '/checkin',
    target: '[data-tour="checkin-wellbeing"]',
    title: 'Wellbeing scales',
    content:
      'Rate overall wellbeing, sleep, and stress. Tap a segment to set today\'s value.',
    placement: 'bottom',
  },
  {
    id: 'gut',
    route: '/checkin',
    target: '[data-tour="checkin-gut"]',
    title: 'Gut health',
    content:
      'Track bloating, stool status, Bristol type, and completeness on the same daily entry.',
    placement: 'bottom',
  },
  {
    id: 'food',
    route: '/checkin',
    target: '[data-tour="checkin-food"]',
    title: 'Food & diet',
    content:
      'Snap meal photos for AI analysis, pick from the meal library (no photo), or log again from history. Diet-risk tags flag high-histamine, FODMAP, gluten, and dairy items.',
    placement: 'bottom',
  },
  {
    id: 'supplements',
    route: '/checkin',
    target: '[data-tour="checkin-supplements"]',
    title: 'Supplements & medications',
    content:
      'Tap pills to mark what you took today. Add or change your catalog anytime in Customize.',
    placement: 'bottom',
  },
  {
    id: 'symptoms',
    route: '/checkin',
    target: '[data-tour="checkin-symptoms"]',
    title: 'Symptoms & trackers',
    content:
      'Log symptom severity and lifestyle trackers you chose during setup. Add more anytime in Customize.',
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
    target: '[data-tour="profile-tab"]',
    title: 'Your profile',
    content:
      'The Profile tab shows your check-in streak, this week at a glance, how your metrics are trending, and your meal log. Its ☰ menu opens Settings and activity — account, connections, customize, and log out all live there.',
    placement: 'top',
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
    id: 'signals',
    route: '/signals',
    target: '[data-tour="signals-header"]',
    title: 'Signals',
    content:
      'See what drives your outcomes — today\'s prediction, ranked drivers, and trends. Unlocks after a few weeks of check-ins.',
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

export const SETUP_STEP_IDS = new Set(
  TOUR_STEPS.filter((step) => step.stepType === 'setup').map((step) => step.id),
)

export function tourStepsForReplay(): TourStepDefinition[] {
  return TOUR_STEPS.filter((step) => step.stepType !== 'setup')
}

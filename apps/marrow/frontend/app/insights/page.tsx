import { redirect } from 'next/navigation'

interface Props {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export default async function InsightsPage({ searchParams }: Props) {
  const params = await searchParams
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === 'string') qs.set(key, value)
    else if (Array.isArray(value)) value.forEach((v) => qs.append(key, v))
  }
  const suffix = qs.toString()
  redirect(suffix ? `/signals?${suffix}` : '/signals')
}

---
name: shadcn/ui component patterns
description: Which shadcn/ui primitives this project uses and how they're wired up
type: project
---

This project uses a non-standard shadcn/ui setup: `Button` is built on `@base-ui/react/button` (not Radix), so `ButtonPrimitive.Props` is the correct type for spreading. Available UI primitives in `frontend/components/ui/`: badge, button, card, dialog, input, label, radio-group, textarea, stepper (new).

`buttonVariants` from `button.tsx` supports: variant (`default`, `outline`, `secondary`, `ghost`, `destructive`, `link`) and size (`default`, `xs`, `sm`, `lg`, `icon`, `icon-xs`, `icon-sm`, `icon-lg`). Size `icon` is `size-8`; for touch-friendly mobile use `size-11` with `rounded-lg` override.

`cn()` is from `@/lib/utils` — standard clsx/tailwind-merge utility.

**Why:** Knowing the exact variant/size names avoids guessing and breaking builds.
**How to apply:** When building new components that use Button, import from `@/components/ui/button` and use the cva variants directly.

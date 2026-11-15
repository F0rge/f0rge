import type { ReactNode } from "react";
import { BaseStyles, ThemeProvider } from "@primer/react";
export {
  Button,
  FormControl,
  TextInput,
  Textarea,
  Select,
  Checkbox,
  Flash,
  Spinner,
  Heading,
  Text,
  Label,
  Link,
  LinkButton,
  UnderlineNav,
  Stack,
  Details,
  Dialog,
} from "@primer/react";

/** Actual Primer defaults; app screens compose these bricks without a brand skin. */
export function PrimerProvider({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider colorMode="auto" dayScheme="light" nightScheme="dark">
      <BaseStyles>{children}</BaseStyles>
    </ThemeProvider>
  );
}

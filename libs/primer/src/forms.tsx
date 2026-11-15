import { createFormHook, createFormHookContexts } from "@tanstack/react-form";
import { Button, FormControl, TextInput } from "@primer/react";
import { publicFieldErrors } from "./validation";

const { fieldContext, formContext, useFieldContext, useFormContext } =
  createFormHookContexts();
function TextField({
  label,
  type = "text",
  required = false,
  caption,
  serverError,
}: {
  label: string;
  type?: "text" | "number" | "date" | "url";
  required?: boolean;
  caption?: string;
  serverError?: string;
}) {
  const field = useFieldContext<string>();
  const errors = [
    ...publicFieldErrors(field.state.meta.errors),
    ...(serverError ? [serverError] : []),
  ];
  return (
    <FormControl required={required}>
      <FormControl.Label>{label}</FormControl.Label>
      <TextInput
        name={field.name}
        value={field.state.value}
        type={type}
        required={required}
        block
        onBlur={field.handleBlur}
        onChange={(event) => field.handleChange(event.target.value)}
        aria-invalid={errors.length > 0}
      />
      {caption && <FormControl.Caption>{caption}</FormControl.Caption>}
      {errors.map((error) => (
        <FormControl.Validation key={error} variant="error">
          {error}
        </FormControl.Validation>
      ))}
    </FormControl>
  );
}
function SubmitButton({ children }: { children: string }) {
  const form = useFormContext();
  return (
    <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
      {([canSubmit, submitting]) => (
        <Button
          type="submit"
          variant="primary"
          disabled={!canSubmit || submitting}
        >
          {submitting ? "Saving…" : children}
        </Button>
      )}
    </form.Subscribe>
  );
}
export const { useAppForm: usePrimerForm } = createFormHook({
  fieldContext,
  formContext,
  fieldComponents: { TextField },
  formComponents: { SubmitButton },
});

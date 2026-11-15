export function publicFieldErrors(errors: readonly unknown[]): string[] {
  return errors.flatMap((error) =>
    typeof error === "string"
      ? [error]
      : typeof error === "object" &&
          error !== null &&
          "message" in error &&
          typeof error.message === "string"
        ? [error.message]
        : [],
  );
}

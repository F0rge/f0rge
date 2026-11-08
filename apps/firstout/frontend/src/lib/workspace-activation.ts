interface WorkspaceClerk {
  setActive(options: {
    organization: string;
    navigate(params: { decorateUrl(url: string): string }): void | Promise<unknown>;
  }): Promise<void>;
  navigate(url: string): void | Promise<unknown>;
}

export async function activateWorkspace(clerk: WorkspaceClerk, organisationId: string, destination: string) {
  await clerk.setActive({
    organization: organisationId,
    // Wait for Next's transition before Clerk refreshes the route. Clerk also
    // handles full navigation when decorateUrl returns an external URL.
    navigate: ({ decorateUrl }) => clerk.navigate(decorateUrl(destination)),
  });
}

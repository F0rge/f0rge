import type { UpdateUserPayload, User } from "./api";

export type UserEditForm = {
  email: string;
  display_name: string;
  role: string;
  password: string;
  default_location_id: string;
};

/** Role changes must not accidentally request changes to a shared identity. */
export function userEditPayload(user: User, form: UserEditForm): UpdateUserPayload {
  const payload: UpdateUserPayload = { role: form.role };
  if (form.email !== user.email) payload.email = form.email;
  if (form.display_name !== user.display_name) payload.display_name = form.display_name;
  if (form.password) payload.password = form.password;
  const location = form.default_location_id || null;
  if (location !== (user.default_location_id ?? null)) payload.default_location_id = location;
  return payload;
}

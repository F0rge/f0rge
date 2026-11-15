import type { Meta, StoryObj } from "@storybook/react";
import { Button, Flash, FormControl, TextInput, Label, Spinner } from "./index";
import { usePrimerForm } from "./forms";
const meta = { title: "Primer/Bricks", component: Button } satisfies Meta<
  typeof Button
>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Actions: Story = {
  render: () => (
    <>
      <Button variant="primary">Save</Button> <Button disabled>Pending</Button>{" "}
      <Button variant="danger">Delete</Button>
    </>
  ),
};
export const States: Story = {
  render: () => (
    <>
      <Flash variant="danger">Permission denied.</Flash>
      <Flash variant="warning">Edit conflict. Reload before saving.</Flash>
      <Flash variant="success">Saved.</Flash>
      <Spinner aria-label="Loading" />
      <Label>Missing observation</Label>
    </>
  ),
};
export const Field: Story = {
  render: () => (
    <FormControl>
      <FormControl.Label>Price</FormControl.Label>
      <TextInput defaultValue="" />
      <FormControl.Validation variant="error">
        Enter a valid price.
      </FormControl.Validation>
    </FormControl>
  ),
};
function FormExample() {
  const form = usePrimerForm({
    defaultValues: { name: "" },
    onSubmit: async () => {
      await Promise.resolve();
    },
  });
  return (
    <form.AppForm>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <form.AppField
          name="name"
          validators={{
            onChange: ({ value }) =>
              value.trim() ? undefined : "Name is required.",
          }}
        >
          {(field) => <field.TextField label="Name" required />}
        </form.AppField>
        <form.SubmitButton>Save</form.SubmitButton>
      </form>
    </form.AppForm>
  );
}
export const TanStackForm: Story = { render: () => <FormExample /> };

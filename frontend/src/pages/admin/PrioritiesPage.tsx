import { TitleResourceManager } from "../../components/admin/TitleResourceManager";
import { createPriority, fetchPriorities, updatePriority } from "../../api/priorities";

export function PrioritiesPage() {
  return (
    <TitleResourceManager
      resourceName="Priority"
      resourceNamePlural="Priorities"
      fetchAll={fetchPriorities}
      create={createPriority}
      update={(id, patch) => updatePriority(id, patch.title ?? "")}
    />
  );
}

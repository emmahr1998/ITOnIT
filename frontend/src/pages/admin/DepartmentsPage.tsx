import { TitleResourceManager } from "../../components/admin/TitleResourceManager";
import { createDepartment, fetchDepartments, updateDepartment } from "../../api/departments";

export function DepartmentsPage() {
  return (
    <TitleResourceManager
      resourceName="Department"
      fetchAll={fetchDepartments}
      create={createDepartment}
      update={(id, patch) => updateDepartment(id, patch.title ?? "")}
    />
  );
}

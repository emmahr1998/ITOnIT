import { apiClient } from "./client";
import type { Category } from "../types/category";

/** GET /categories returns a bare list - no {data, msg} envelope. */
export async function fetchCategories(): Promise<Category[]> {
  const { data } = await apiClient.get<Category[]>("/categories");
  return data;
}

/** POST /categories returns a bare CategoryResponse. */
export async function createCategory(name: string, description: string | null): Promise<Category> {
  const { data } = await apiClient.post<Category>("/categories", { name, description });
  return data;
}

/** PUT /categories/{id} is a full replacement, not a partial patch. */
export async function updateCategory(
  categoryId: number,
  name: string,
  description: string | null,
): Promise<Category> {
  const { data } = await apiClient.put<Category>(`/categories/${categoryId}`, {
    name,
    description,
  });
  return data;
}

export async function deleteCategory(categoryId: number): Promise<void> {
  await apiClient.delete(`/categories/${categoryId}`);
}

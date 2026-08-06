/** Mirrors backend/app/schemas/response.py - the {data, msg} envelope used by some endpoints. */
export interface DataResponse<T> {
  data: T;
  msg: string;
}

export type ErrorCode =
  | 'VALIDATION_ERROR'
  | 'NOT_FOUND'
  | 'FORBIDDEN'
  | 'CONFLICT'
  | 'UNAUTHORIZED'
  | 'INTERNAL_ERROR';

export type ActionResult<T> =
  | { success: true; data: T }
  | { success: false; error: string; code?: ErrorCode };

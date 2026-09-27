export type ClosureVerificationResult =
  | "effective"
  | "partially_effective"
  | "not_effective";

export type ClosureStatus = "closed" | "re_opened";

export type ClosureVerification = {
  id: string;
  corrective_action_id: string;
  verification_date: string;
  verification_result: ClosureVerificationResult;
  closure_status: ClosureStatus;
  notes: string;
  verified_by_user_id?: string | null;
  verified_by?: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateClosureVerificationRequest = {
  verification_date: string;
  verification_result: ClosureVerificationResult;
  closure_status: ClosureStatus;
  notes: string;
};

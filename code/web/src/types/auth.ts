export interface FarmSummary {
  id: number;
  name: string;
  timezone: string;
}

export interface CurrentUser {
  id: number;
  username: string;
  display_name: string;
  status: string;
  farm: FarmSummary;
  roles: string[];
}

export interface LoginPayload {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: CurrentUser;
}

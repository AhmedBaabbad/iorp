import { apiClient } from "@/lib/api-client";

export type TenantAuditEvent = {id:string;occurred_at:string;event_type:string;category:string;outcome:string;severity:string;actor_type:string;actor_id:string|null;actor_email_snapshot:string|null;actor_name_snapshot:string|null;target_type:string|null;target_id:string|null;target_display_snapshot:string|null;organization_id:string;request_id:string|null;correlation_id:string|null;ip_address:string|null;user_agent:string|null;reason:string|null;changes:unknown;metadata:unknown;error_code:string|null};
export type TenantAuditList={items:TenantAuditEvent[];total:number;page:number;page_size:number;pages:number};
export const listTenantAudit=(query:URLSearchParams,token?:string|null)=>apiClient<TenantAuditList>(`/admin/audit-log?${query}`,{token});
export const getTenantAudit=(id:string,token?:string|null)=>apiClient<TenantAuditEvent>(`/admin/audit-log/${id}`,{token});

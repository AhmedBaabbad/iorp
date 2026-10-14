import {ComplaintCreate} from "@/features/complaints/ComplaintsPage";
export default async function Page({searchParams}:{searchParams:Promise<{customer_id?:string}>}){const params=await searchParams;return <ComplaintCreate customerId={params.customer_id}/>;}

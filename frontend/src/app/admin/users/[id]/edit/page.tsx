"use client";
import {useEffect} from "react";
import {useParams,useRouter} from "next/navigation";
export default function Page(){const {id}=useParams<{id:string}>();const router=useRouter();useEffect(()=>{router.replace(`/admin/users/${id}`);},[id,router]);return null;}

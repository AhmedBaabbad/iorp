import type {Page} from "@/lib/pagination";
import {queryString, type PageQuery} from "@/lib/page-response";
import { apiClient } from "@/lib/api-client";
import type { ParameterInput, ParameterUpdate, Specification, SpecificationInput, SpecificationListItem, SpecificationStatus, TestParameter } from "./types";

const PARAMS = "/quality/quality-test-parameters";
const SPECS = "/quality/quality-specifications";

export function getParameters(active:boolean,filters:PageQuery):Promise<Page<TestParameter>>;
export function getParameters(active?:boolean):Promise<TestParameter[]>;
export function getParameters(active=false,filters?:PageQuery){return apiClient<TestParameter[]|Page<TestParameter>>(`${PARAMS}${queryString({...filters,...(active?{active:true}:{})})}`);}
export const createParameter = (body: ParameterInput) => apiClient<TestParameter>(PARAMS, { method: "POST", body });
export const updateParameter = (id: string, body: ParameterUpdate) => apiClient<TestParameter>(`${PARAMS}/${id}`, { method: "PATCH", body });
// Width, thickness, weight, length, strength, elongation and the visual checks; codes already present are left alone.
export const addStandardParameters = () => apiClient<TestParameter[]>(`${PARAMS}/standard`, { method: "POST" });

export function getSpecifications(filters:PageQuery):Promise<Page<SpecificationListItem>>;
export function getSpecifications(filters?:{status?:SpecificationStatus|"";search?:string}):Promise<SpecificationListItem[]>;
export function getSpecifications(filters:object={}){return apiClient<SpecificationListItem[]|Page<SpecificationListItem>>(`${SPECS}${queryString(filters)}`);}
export const getSpecification = (id: string) => apiClient<Specification>(`${SPECS}/${id}`);
export const createSpecification = (body: SpecificationInput) => apiClient<Specification>(SPECS, { method: "POST", body });
export const updateSpecification = (id: string, body: Omit<SpecificationInput, "code">) => apiClient<Specification>(`${SPECS}/${id}`, { method: "PATCH", body });
// Puts the draft into force; the revision in force with the same code becomes superseded.
export const activateSpecification = (id: string) => apiClient<Specification>(`${SPECS}/${id}/activate`, { method: "POST" });
// A new draft revision copying the lines.
export const reviseSpecification = (id: string) => apiClient<Specification>(`${SPECS}/${id}/revise`, { method: "POST" });

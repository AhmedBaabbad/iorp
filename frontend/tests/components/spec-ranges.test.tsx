import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeAll, expect, it } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { NumericSpecInput } from "@/components/forms/NumericSpecInput";
import { formatSpecValue, parseNumericSpec, thicknessFields } from "@/lib/spec-value";
import { parseSpecValue, rowsToSpec, specToRows, templateSpec } from "@/lib/spec-rows";
import {SpecEditor} from "@/components/forms/SpecEditor";

let messages: Awaited<ReturnType<typeof loadMessages>>;
beforeAll(async () => { messages = await loadMessages("en"); });
afterEach(cleanup);

it.each(["0.55-0.60", "0.55 - 0.60", "0.55–0.60", "٠٫٥٥-٠٫٦٠"])("parses %s to a numeric object", text => {
  expect(parseNumericSpec(text, true)).toEqual({ min: .55, max: .6 });
});
it("rejects reversed, nonnumeric and non-opt-in ranges, and normalizes equal endpoints", () => {
  expect(() => parseNumericSpec("0.60-0.55", true)).toThrow("SPEC_RANGE_REVERSED");
  expect(() => parseNumericSpec("bad", true)).toThrow("SPEC_RANGE_NUMBER");
  expect(() => parseNumericSpec("0.55-0.60")).toThrow("SPEC_RANGE_NOT_ALLOWED");
  expect(parseNumericSpec("0.55-0.55", true)).toBe(.55);
  expect(parseNumericSpec("٠٫٥٥")).toBe(.55);
  expect(formatSpecValue({ min: .55, max: .6 })).toBe("0.55 – 0.60");
  expect(formatSpecValue(.55)).toBe("0.55");
  expect(thicknessFields("0.55-0.60")).toEqual({ thickness_mm: "0.55", thickness_max_mm: "0.6" });
});
it("preserves free-text intervals and legacy text while still parsing scalar digits", () => {
  expect(parseSpecValue("10-20")).toBe("10-20");
  expect(parseSpecValue("٠٫٥٥")).toBe(.55);
  const rows = [{ key: "legacy", value: "10-20" }];
  expect(JSON.parse(rowsToSpec(rows))).toEqual({ legacy: "10-20" });
  expect(specToRows(rowsToSpec(rows))).toEqual(rows);
  expect(JSON.parse(templateSpec([], {}, rows))).toEqual({ legacy: "10-20" });
});
it("creates range objects only for opted-in numeric template properties", () => {
  const template = [{ key: "thickness", name_ar: "السماكة", name_en: "Thickness", kind: "number" as const, unit: "mm", required: false, allows_range: true, options: null }];
  const json = templateSpec(template, { thickness: "0.55-0.60" }, [{ key: "legacy", value: "10-20" }]);
  expect(JSON.parse(json)).toEqual({ thickness: { min: .55, max: .6 }, legacy: "10-20" });
  expect(specToRows(json)[0].value).toBe("0.55 – 0.60");
  expect(templateSpec(template, { thickness: specToRows(json)[0].value }, [])).toBe('{"thickness":{"min":0.55,"max":0.6}}');
  expect(JSON.parse(templateSpec([{ ...template[0], allows_range: false }], { thickness: "0.55-0.60" }, []))).toEqual({ thickness: "0.55-0.60" });
});
function Input() {
  const [value, setValue] = useState("");
  return <NumericSpecInput aria-label="Thickness" value={value} onValueChange={setValue} allowsRange />;
}
it("keeps incomplete input editable and reports translated validity errors", () => {
  render(<NextIntlClientProvider locale="en" messages={messages}><Input /></NextIntlClientProvider>);
  const input = screen.getByRole("textbox", { name: "Thickness" }) as HTMLInputElement;
  fireEvent.change(input, { target: { value: "0.60-0.55" } });
  expect(input.checkValidity()).toBe(false);
  fireEvent.blur(input);
  expect(screen.getByRole("alert").textContent).toContain("minimum");
  fireEvent.change(input, { target: { value: "٠٫٥٥-٠٫٦٠" } });
  expect(input.checkValidity()).toBe(true);
  expect(screen.queryByRole("alert")).toBeNull();
});

it("keeps every typed trailing zero and emits a numeric interval only on blur",()=>{
  let latest='';
  const template=[{key:'thickness_mm',name_ar:'السماكة',name_en:'Thickness',kind:'number' as const,unit:null,required:false,allows_range:true,options:null}];
  function Editor(){const [value,setValue]=useState('');return <SpecEditor value={value} template={template} onChange={next=>{latest=next;setValue(next);}}/>;}
  render(<NextIntlClientProvider locale="en" messages={messages}><Editor/></NextIntlClientProvider>);
  const field=screen.getByRole('textbox',{name:'Thickness'}) as HTMLInputElement;
  let typed='';for(const char of '0.70-0.75'){typed+=char;fireEvent.change(field,{target:{value:typed}});expect(field.value).toBe(typed);expect(JSON.parse(latest).thickness_mm).toBe(typed);}
  fireEvent.blur(field);
  expect(JSON.parse(latest)).toEqual({thickness_mm:{min:.7,max:.75}});
  expect(field.value).toBe('0.70-0.75');
});

it("formats saved intervals and preserves untouched historical objects when another field changes",()=>{
  let latest='';
  const stored={thickness_mm:{min:.7,max:.75},legacy:{nested:'Kept'}};
  render(<NextIntlClientProvider locale="en" messages={messages}><SpecEditor value={JSON.stringify(stored)} onChange={next=>{latest=next;}}/></NextIntlClientProvider>);
  const values=screen.getAllByRole('textbox',{name:'Value'}) as HTMLInputElement[];
  expect(values[0].value).toBe('0.70 – 0.75');
  fireEvent.blur(values[0]);
  expect(JSON.parse(latest)).toEqual(stored);
});

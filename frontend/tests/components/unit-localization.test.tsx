import {expect,it} from 'vitest';
import {formatUnit} from '@/lib/localized-units';
import {formatQuantity} from '@/lib/formatters';
import {UNITS} from '@/lib/units';
import ar from '@/i18n/locales/ar/common.json';
import en from '@/i18n/locales/en/common.json';
it('localizes quantities and preserves canonical codes and decimals behavior',()=>{expect(formatQuantity(185,'roll','ar')).toBe('185 لفة');expect(formatQuantity(185,'roll','en')).toBe('185 roll');expect(formatQuantity(0,'roll','ar')).toBe('0 لفة');});
it('uses the shared catalogue for every unit in both languages',()=>{for(const code of UNITS){expect(formatUnit(code,'ar')).toBe((ar.units.units as Record<string,string>)[code]);expect(formatUnit(code,'en')).toBe((en.units.units as Record<string,string>)[code]);}});
it('preserves custom units and handles legacy capitalization',()=>{expect(formatUnit('ROLL','ar')).toBe('لفة');expect(formatUnit('N/mm²','ar')).toBe('N/mm²');expect(formatUnit(null,'ar')).toBe('');expect(formatUnit('لفة','ar')).toBe('لفة');});

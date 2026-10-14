// Waiting budget for asynchronous queries (findBy*, waitFor): role queries over a large form are slow in jsdom when the
// whole suite runs in parallel; 1 s (the library default) made correct tests fail under load. Assertions are unchanged.
import { configure } from "@testing-library/react";

configure({ asyncUtilTimeout: 5000 });

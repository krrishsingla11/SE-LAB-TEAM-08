# Accessibility audit (SE8-41)

Date: 6 Nov 2026. Scope: all 11 frontend pages, at 1280px and 375px width.

## Method
- **axe-core 4.14.0** run in headless Chromium with the rules for WCAG 2.0 A/AA, 2.1 A/AA, 2.2 AA and best practices.
- Pages were tested with real data from the running backend: logged out, as a buyer and as an artisan. The dashboard was tested in sample-data mode and against the real server.
- Error states were tested too (empty forms, declined card, wrong password), because axe only checks what is on screen.
- Keyboard test: pressed Tab through every page and checked that each stop shows a focus indicator, and that the skip link works.
- Contrast was measured by axe on the real rendered colours. The Tailwind CDN was not reachable in the test environment, so the same utility classes were compiled locally and injected.

## Result
| | Before fixes | After fixes |
|---|---|---|
| Violations on 11 pages x 2 widths | 1 type (serious), 3 buttons on the dashboard | 0 |
| Violations in error states | not tested | 0 |
| Horizontal scrolling at 375px | none | none |
| Tab stops without a visible focus indicator | 0 | 0 |

## Fixes made
1. **Dashboard status buttons (WCAG 2.5.3 Label in Name):** the spoken label did not contain the visible text ("Mark as Shipped"). The label is now "Mark as Shipped, order 57".
2. **Skip link (2.4.1):** added "Skip to main content" as the first Tab stop on every page.
3. **Form errors (3.3.1):** each input is now linked to its error message with aria-describedby, and focus moves to the first invalid field when a form fails validation.
4. **Layout:** extra spacing under the product image on phones.

## Already in place
Labels on every input, one h1 per page, landmarks (header, nav, main), page titles, language set, live regions for loading and status messages, aria-current on the active menu item and order step, text (not colour alone) for stock and order status.

## Not covered
- No testing with real screen readers (NVDA, VoiceOver, TalkBack).
- No testing on real phones, at 200 to 400 percent zoom, or in Windows high-contrast mode.
- Automated tools find roughly a third of accessibility problems, so a manual review is still advised.
- Product photos use a letter placeholder when no image exists; real photos get the product title as alt text.

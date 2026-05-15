"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = __importDefault(require("react"));
const Header_module_css_1 = __importDefault(require("./Header.module.css"));
const Header = () => {
    return ((0, jsx_runtime_1.jsx)("header", { className: Header_module_css_1.default.header, children: (0, jsx_runtime_1.jsxs)("div", { className: `container ${Header_module_css_1.default.container}`, children: [(0, jsx_runtime_1.jsxs)("div", { className: Header_module_css_1.default.logo, children: [(0, jsx_runtime_1.jsx)("span", { className: Header_module_css_1.default.brand, children: "\u05E7\u05E9\u05E8" }), (0, jsx_runtime_1.jsx)("span", { className: Header_module_css_1.default.subtitle, children: "\u05E9\u05D9\u05E8\u05D4 \u05E1\u05D4\u05E8\u05D5\u05E0\u05D9" })] }), (0, jsx_runtime_1.jsxs)("nav", { className: Header_module_css_1.default.nav, children: [(0, jsx_runtime_1.jsx)("a", { href: "#about", children: "\u05D0\u05D5\u05D3\u05D5\u05EA" }), (0, jsx_runtime_1.jsx)("a", { href: "#services", children: "\u05E9\u05D9\u05E8\u05D5\u05EA\u05D9\u05DD" }), (0, jsx_runtime_1.jsx)("a", { href: "#blog", children: "\u05D1\u05DC\u05D5\u05D2" }), (0, jsx_runtime_1.jsx)("a", { href: "#contact", className: Header_module_css_1.default.cta, children: "\u05E7\u05D1\u05D9\u05E2\u05EA \u05E4\u05D2\u05D9\u05E9\u05D4" })] })] }) }));
};
exports.default = Header;
//# sourceMappingURL=Header.js.map
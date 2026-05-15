"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = __importDefault(require("react"));
const Hero_1 = __importDefault(require("./Hero"));
const Home_module_css_1 = __importDefault(require("./Home.module.css"));
const Home = () => {
    return ((0, jsx_runtime_1.jsxs)("div", { className: Home_module_css_1.default.home, children: [(0, jsx_runtime_1.jsx)(Hero_1.default, {}), (0, jsx_runtime_1.jsx)("section", { id: "services", className: Home_module_css_1.default.section, children: (0, jsx_runtime_1.jsxs)("div", { className: "container", children: [(0, jsx_runtime_1.jsx)("h2", { children: "\u05D4\u05E9\u05D9\u05E8\u05D5\u05EA\u05D9\u05DD \u05E9\u05DC\u05E0\u05D5" }), (0, jsx_runtime_1.jsx)("p", { children: "\u05D1\u05E7\u05E8\u05D5\u05D1 \u05D9\u05D5\u05E4\u05D9\u05E2\u05D5 \u05DB\u05D0\u05DF \u05E4\u05E8\u05D8\u05D9\u05DD \u05E2\u05DC \u05D9\u05D9\u05E2\u05D5\u05E5 \u05D6\u05D5\u05D2\u05D9, \u05D4\u05D3\u05E8\u05DB\u05EA \u05D4\u05D5\u05E8\u05D9\u05DD \u05D5\u05D2\u05D9\u05E9\u05D5\u05E8." })] }) })] }));
};
exports.default = Home;
//# sourceMappingURL=Home.js.map
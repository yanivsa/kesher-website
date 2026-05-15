"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = __importDefault(require("react"));
const Header_1 = __importDefault(require("./Header"));
const Footer_1 = __importDefault(require("./Footer"));
const FloatingWhatsApp_1 = __importDefault(require("./FloatingWhatsApp"));
const Layout_module_css_1 = __importDefault(require("./Layout.module.css"));
const Layout = ({ children }) => {
    return ((0, jsx_runtime_1.jsxs)("div", { className: Layout_module_css_1.default.wrapper, children: [(0, jsx_runtime_1.jsx)(Header_1.default, {}), (0, jsx_runtime_1.jsx)("main", { className: Layout_module_css_1.default.main, children: children }), (0, jsx_runtime_1.jsx)(Footer_1.default, {}), (0, jsx_runtime_1.jsx)(FloatingWhatsApp_1.default, {})] }));
};
exports.default = Layout;
//# sourceMappingURL=Layout.js.map
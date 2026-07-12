/** @type {import('next').NextConfig} */
const nextConfig = {
  // StrictMode double-mounts components in dev; the second mount tears down
  // the first Plotly mapbox-gl instance mid style-load and crashes it
  // ("Cannot read properties of undefined (reading 'version')").
  reactStrictMode: false,
};

export default nextConfig;

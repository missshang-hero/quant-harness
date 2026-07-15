const isDesktopExport = process.env.NEXT_DESKTOP_EXPORT === '1'

const nextConfig = isDesktopExport
  ? {
      images: {
        unoptimized: true,
      },
      output: 'export',
      trailingSlash: true,
    }
  : {}

export default nextConfig

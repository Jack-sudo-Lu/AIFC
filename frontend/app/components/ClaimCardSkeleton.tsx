export default function ClaimCardSkeleton() {
  return (
    <div className="bg-white rounded-xl shadow-lg p-6 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-3 bg-gray-200 rounded w-1/4" />
        </div>
        <div className="h-6 w-20 bg-gray-200 rounded-full ml-3" />
      </div>
      <div className="mb-3">
        <div className="h-3 bg-gray-200 rounded w-1/3 mb-1" />
        <div className="h-2 bg-gray-200 rounded-full" />
      </div>
      <div className="space-y-1">
        <div className="h-3 bg-gray-200 rounded w-full" />
        <div className="h-3 bg-gray-200 rounded w-5/6" />
      </div>
    </div>
  );
}

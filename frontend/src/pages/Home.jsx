import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Star, ArrowRight } from "lucide-react";
import apiClient from "../api/client";
import Container from "../components/ui/Container";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Divider from "../components/ui/Divider";
import SearchBar from "../components/SearchBar";
import ProductCard from "../components/ProductCard";

/**
 * Neo-Brutalist Home page.
 * Hero section + search + product grid.
 * VULN: Reflected XSS in search query display.
 */
export default function Home() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const query = searchParams.get("q") || "";
  const category = searchParams.get("category") || "";

  useEffect(() => {
    fetchProducts();
  }, [query, category, page]);

  // VULN: Reflected XSS - Search query injected into document.title without escaping - Ref: https://hackerone.com/reports/111094
  useEffect(() => {
    if (query) {
      document.title = `VulnShop - Search: ${query}`;
    } else {
      document.title = "VulnShop";
    }
  }, [query]);

  async function fetchProducts() {
    setIsLoading(true);
    try {
      const params = { page, per_page: 9 };
      if (query) params.q = query;
      if (category) params.category = category;
      const response = await apiClient.get("/products", { params });
      setProducts(response.data.products || response.data.items || []);
      const total = response.data.total || 0;
      const perPage = response.data.limit || 9;
      setTotalPages(Math.ceil(total / perPage) || 1);
    } catch {
      setProducts([]);
    } finally {
      setIsLoading(false);
    }
  }

  async function fetchCategories() {
    try {
      const response = await apiClient.get("/products/categories");
      setCategories(response.data || []);
    } catch {
      setCategories([]);
    }
  }

  useEffect(() => {
    fetchCategories();
  }, []);

  function handleSearch(q) {
    setPage(1);
    setSearchParams(q ? { q } : {});
  }

  function handleCategoryFilter(cat) {
    setPage(1);
    const params = {};
    if (query) params.q = query;
    if (cat && cat !== category) params.category = cat;
    setSearchParams(params);
  }

  async function handleAddToCart(productId) {
    try {
      await apiClient.post("/cart/items", { product_id: productId, quantity: 1 });
    } catch {
      // Error logged by axios interceptor
    }
  }

  return (
    <main>
      {/* HERO SECTION */}
      <section className="relative overflow-hidden border-b-8 border-black bg-neo-secondary">
        <div className="absolute inset-0 bg-halftone opacity-5" />
        <Container className="relative py-16 sm:py-24">
          <div className="grid grid-cols-1 items-center gap-8 lg:grid-cols-5">
            {/* Text side (60%) */}
            <div className="lg:col-span-3">
              <h1 className="font-black text-6xl uppercase leading-none tracking-tighter sm:text-8xl">
                <span className="block">SHOP</span>
                <span className="block text-stroke-3">BRUTAL</span>
              </h1>
              <p className="mt-4 max-w-md text-xl font-bold">
                The most deliberately vulnerable e-commerce platform.
                Built for security testing.
              </p>
              <Button
                variant="primary"
                size="lg"
                className="mt-6 shadow-neo-lg"
                onClick={() => {
                  document
                    .getElementById("products")
                    ?.scrollIntoView({ behavior: "smooth" });
                }}
              >
                BROWSE PRODUCTS <ArrowRight className="ml-2 inline h-5 w-5" strokeWidth={3} />
              </Button>
            </div>

            {/* Decorative side (40%) */}
            <div className="relative hidden h-64 lg:col-span-2 lg:block">
              <div className="absolute left-8 top-4 h-24 w-24 rotate-12 border-4 border-black bg-neo-accent" />
              <div className="absolute right-12 top-8 h-20 w-20 rounded-full border-4 border-black bg-neo-muted" />
              <Star
                className="absolute bottom-4 left-16 h-16 w-16 animate-spin-slow text-black"
                strokeWidth={3}
              />
              <Badge
                variant="accent"
                rotation="rotate-3"
                className="absolute bottom-8 right-4"
              >
                NEW DROPS
              </Badge>
            </div>
          </div>
        </Container>
      </section>

      {/* SEARCH SECTION */}
      <section className="border-b-4 border-black bg-neo-bg py-8">
        <Container>
          <SearchBar onSearch={handleSearch} initialQuery={query} />

          {/* Category filters */}
          {categories.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge
                variant={!category ? "dark" : "muted"}
                pill
                className="cursor-pointer"
                onClick={() => handleCategoryFilter("")}
              >
                ALL
              </Badge>
              {categories.map((cat) => (
                <Badge
                  key={cat}
                  variant={category === cat ? "dark" : "muted"}
                  pill
                  className="cursor-pointer"
                  onClick={() => handleCategoryFilter(cat)}
                >
                  {cat}
                </Badge>
              ))}
            </div>
          )}

          {/* VULN: Reflected XSS - Search query rendered with dangerouslySetInnerHTML - Ref: https://hackerone.com/reports/111094 */}
          {query && (
            <div className="mt-4 flex items-center gap-2">
              <Badge variant="secondary">RESULTS FOR:</Badge>
              <span
                className="font-black text-xl"
                dangerouslySetInnerHTML={{ __html: query }}
              />
            </div>
          )}
        </Container>
      </section>

      {/* PRODUCTS GRID */}
      <section id="products" className="bg-neo-bg py-16">
        <Container>
          <div className="mb-8">
            <h2 className="font-black text-5xl uppercase tracking-tight">
              PRODUCTS
            </h2>
            <div className="-rotate-1 mt-1 h-3 w-32 bg-neo-accent" />
          </div>

          {isLoading ? (
            <div className="py-16 text-center">
              <p className="animate-bounce-slow font-black text-3xl uppercase">
                LOADING...
              </p>
            </div>
          ) : products.length === 0 ? (
            <div className="py-16 text-center">
              <p className="font-black text-3xl uppercase text-black/30">
                NO PRODUCTS FOUND
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
                {products.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    onAddToCart={handleAddToCart}
                  />
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="mt-12 flex justify-center gap-2">
                  {Array.from({ length: totalPages }, (_, i) => (
                    <Button
                      key={i + 1}
                      variant={page === i + 1 ? "dark" : "outline"}
                      size="sm"
                      className="h-12 w-12"
                      onClick={() => setPage(i + 1)}
                    >
                      {i + 1}
                    </Button>
                  ))}
                </div>
              )}
            </>
          )}
        </Container>
      </section>

      <Divider marquee text="SHOP BRUTAL — HACK EVERYTHING — FIND THE VULNS" />
    </main>
  );
}

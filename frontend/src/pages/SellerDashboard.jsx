import { useState, useEffect } from "react";
import { Trash2, Edit, Link as LinkIcon } from "lucide-react";
import apiClient from "../api/client";
import Container from "../components/ui/Container";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import ImageUpload from "../components/ImageUpload";

const TABS = ["MY PRODUCTS", "ADD PRODUCT", "IMPORT IMAGE URL", "ANALYTICS"];

/**
 * Neo-Brutalist seller dashboard.
 * Tabs: My Products, Add Product, Import Image URL, Analytics.
 */
export default function SellerDashboard() {
  const [activeTab, setActiveTab] = useState(0);
  const [products, setProducts] = useState([]);
  const [stats, setStats] = useState({ total_sales: 0, avg_rating: 0 });
  const [message, setMessage] = useState("");

  // Add product form
  const [newProduct, setNewProduct] = useState({
    name: "",
    description: "",
    price: "",
    category: "",
    stock: "",
  });
  const [productImage, setProductImage] = useState(null);

  // Import URL
  const [imageUrl, setImageUrl] = useState("");

  useEffect(() => {
    fetchProducts();
    fetchStats();
  }, []);

  async function fetchProducts() {
    try {
      const response = await apiClient.get("/products/seller/me");
      setProducts(response.data || []);
    } catch {
      setProducts([]);
    }
  }

  async function fetchStats() {
    try {
      const response = await apiClient.get("/products/seller/stats");
      setStats(response.data || { total_sales: 0, avg_rating: 0 });
    } catch {
      // Silently fail
    }
  }

  async function handleAddProduct(e) {
    e.preventDefault();
    setMessage("");
    try {
      const formData = new FormData();
      formData.append("name", newProduct.name);
      formData.append("description", newProduct.description);
      formData.append("price", newProduct.price);
      formData.append("category", newProduct.category);
      formData.append("stock", newProduct.stock);
      if (productImage) formData.append("image", productImage);

      await apiClient.post("/products", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setMessage("Product created!");
      setNewProduct({ name: "", description: "", price: "", category: "", stock: "" });
      setProductImage(null);
      fetchProducts();
    } catch (err) {
      setMessage(err.response?.data?.detail || "Failed to create product");
    }
  }

  async function handleDeleteProduct(productId) {
    try {
      await apiClient.delete(`/products/${productId}`);
      fetchProducts();
    } catch {
      // Error logged by interceptor
    }
  }

  async function handleImportUrl(e) {
    e.preventDefault();
    setMessage("");
    try {
      await apiClient.post("/products/import-image", { url: imageUrl });
      setMessage("Image imported!");
      setImageUrl("");
    } catch (err) {
      setMessage(err.response?.data?.detail || "Failed to import image");
    }
  }

  function handleProductChange(e) {
    setNewProduct((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  return (
    <main className="min-h-screen bg-neo-bg py-16">
      <Container>
        <h1 className="mb-8 font-black text-5xl uppercase tracking-tight">
          SELLER DASHBOARD
        </h1>

        {message && (
          <div className="mb-6 border-4 border-black bg-neo-secondary p-4 font-bold">
            {message}
          </div>
        )}

        {/* Tabs */}
        <div className="mb-8 flex flex-wrap gap-2">
          {TABS.map((tab, i) => (
            <Button
              key={tab}
              variant={activeTab === i ? "dark" : "outline"}
              size="sm"
              onClick={() => setActiveTab(i)}
            >
              {tab}
            </Button>
          ))}
        </div>

        {/* My Products */}
        {activeTab === 0 && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {products.length === 0 ? (
              <p className="font-bold text-lg text-black/40">
                NO PRODUCTS YET
              </p>
            ) : (
              products.map((product) => (
                <Card key={product.id} shadow="shadow-neo-sm">
                  <div className="p-4">
                    <h3 className="truncate font-black text-xl uppercase">
                      {product.name}
                    </h3>
                    <p className="mt-1 font-bold text-2xl">
                      ${Number(product.price).toFixed(2)}
                    </p>
                    <div className="mt-4 flex gap-2">
                      <Button variant="outline" size="sm">
                        <Edit className="h-4 w-4" strokeWidth={3} />
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleDeleteProduct(product.id)}
                      >
                        <Trash2 className="h-4 w-4" strokeWidth={3} />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        )}

        {/* Add Product */}
        {activeTab === 1 && (
          <Card header="NEW PRODUCT" headerColor="bg-neo-secondary" shadow="shadow-neo-lg">
            <form onSubmit={handleAddProduct} className="flex flex-col gap-4 p-6">
              <Input label="Name" name="name" value={newProduct.name} onChange={handleProductChange} required />
              <Input label="Description" name="description" type="textarea" value={newProduct.description} onChange={handleProductChange} />
              <div className="grid grid-cols-2 gap-4">
                <Input label="Price" name="price" type="number" step="0.01" value={newProduct.price} onChange={handleProductChange} required />
                <Input label="Stock" name="stock" type="number" value={newProduct.stock} onChange={handleProductChange} required />
              </div>
              <Input label="Category" name="category" value={newProduct.category} onChange={handleProductChange} />
              <ImageUpload onUpload={setProductImage} />
              <Button type="submit" variant="primary" size="lg">
                CREATE PRODUCT
              </Button>
            </form>
          </Card>
        )}

        {/* Import Image URL */}
        {activeTab === 2 && (
          <Card header="IMPORT IMAGE FROM URL" headerColor="bg-neo-muted" shadow="shadow-neo-lg">
            <form onSubmit={handleImportUrl} className="flex flex-col gap-4 p-6">
              <Input
                label="Image URL"
                placeholder="https://example.com/image.jpg"
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                required
              />
              <Button type="submit" variant="secondary">
                <LinkIcon className="mr-2 inline h-5 w-5" strokeWidth={3} />
                FETCH
              </Button>
            </form>
          </Card>
        )}

        {/* Analytics */}
        {activeTab === 3 && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <Card shadow="shadow-neo-lg" className="bg-neo-secondary">
              <div className="p-8 text-center">
                <p className="text-sm font-bold uppercase tracking-widest">
                  TOTAL SALES
                </p>
                <p className="mt-2 font-black text-5xl">
                  {stats.total_sales}
                </p>
              </div>
            </Card>
            <Card shadow="shadow-neo-lg" className="bg-neo-muted">
              <div className="p-8 text-center">
                <p className="text-sm font-bold uppercase tracking-widest">
                  AVG RATING
                </p>
                <p className="mt-2 font-black text-5xl">
                  {Number(stats.avg_rating).toFixed(1)}
                </p>
              </div>
            </Card>
          </div>
        )}
      </Container>
    </main>
  );
}

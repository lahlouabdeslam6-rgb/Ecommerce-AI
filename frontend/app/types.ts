export type User = {
  id: number;
  email: string;
  full_name: string | null;
  role: "customer" | "support" | "admin";
  is_active: boolean;
  is_email_verified: boolean;
  created_at: string;
};

export type Ingredient = {
  name?: string;
  form?: string;
  category?: string;
  amount_per_serving_mg?: number;
};

export type Product = {
  product_id: number;
  brand: string | null;
  name: string | null;
  description: string | null;
  category: string | null;
  price: number | null;
  currency: string;
  stock: number;
  is_active: boolean;
  images: string[];
  videos: string[];
  form_type: string | null;
  ingredients: Ingredient[];
  serving_size?: { count?: number; unit?: string };
  seo_title?: string | null;
  seo_description?: string | null;
  seo_keywords?: string[];
  tags?: string[];
  slug?: string | null;
  image_alt?: string | null;
  seo_faq?: { question: string; answer: string }[];
  ai_model?: string | null;
  ai_generated_at?: string | null;
};

export type ProductList = {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type RecommendationItem = {
  product: Product;
  score: number;
  reasons: string[];
};

export type RecommendationResponse = {
  context: "product" | "cart";
  strategy: "semantic+catalogue" | "catalogue";
  personalized: boolean;
  items: RecommendationItem[];
  disclaimer: string;
};

export type CartItem = {
  product_id: number;
  name: string;
  brand: string | null;
  image_url: string | null;
  unit_price: number;
  currency: string;
  quantity: number;
  subtotal: number;
  stock: number;
  is_available: boolean;
};

export type Cart = {
  items: CartItem[];
  item_count: number;
  subtotal: number;
  currency: string;
};

export type Order = {
  id: number;
  user_id: number | null;
  email: string;
  order_status: string;
  payment_method: string;
  payment_status: string;
  card_last4: string | null;
  card_brand: string | null;
  payment_reference: string | null;
  full_name: string;
  phone: string;
  address: string;
  city: string;
  notes: string | null;
  subtotal: number;
  delivery_fee: number;
  total: number;
  currency: string;
  created_at: string;
  updated_at: string;
  items: Array<{
    product_id: number;
    product_name: string;
    brand: string | null;
    image_url: string | null;
    unit_price: number;
    quantity: number;
    subtotal: number;
  }>;
};

export type GuestCheckoutResponse = {
  order: Order;
  tracking_token: string;
};

export type PaginatedOrders = {
  items: Order[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type TicketMessage = {
  id: number;
  sender_id: number;
  sender_role: "customer" | "support" | "admin";
  sender_name: string;
  message: string;
  created_at: string;
};

export type SupportTicket = {
  id: number;
  user_id: number;
  order_id: number | null;
  customer_name: string;
  customer_email: string;
  subject: string;
  category: string;
  status: "open" | "in_progress" | "resolved" | "closed";
  priority: "low" | "normal" | "high" | "urgent";
  created_at: string;
  updated_at: string;
  messages: TicketMessage[];
};

export type TicketList = {
  items: SupportTicket[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

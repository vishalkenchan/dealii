// ---------------------------------------------------------------------
//
// Copyright (C) 2015 - 2017 by the deal.II authors
//
// This file is part of the deal.II library.
//
// The deal.II library is free software; you can use it, redistribute
// it, and/or modify it under the terms of the GNU Lesser General
// Public License as published by the Free Software Foundation; either
// version 2.1 of the License, or (at your option) any later version.
// The full text of the license can be found in the file LICENSE at
// the top level of the deal.II distribution.
//
// ---------------------------------------------------------------------


#ifndef dealii__fe_rannacher_turek_h
#define dealii__fe_rannacher_turek_h

#include <deal.II/base/polynomials_rannacher_turek.h>
#include <deal.II/fe/fe_poly.h>
#include <deal.II/fe/fe_base.h>
#include <string>
#include <vector>

DEAL_II_NAMESPACE_OPEN


/**
 * Implementation of Rannacher-Turek elements. Functions generated by this
 * element will be discontinuous, but their jump along faces is mean value
 * free.
 *
 * Implemented only in dimension 2, lowest order, without hanging nodes and
 * restriction/prolongation.
 *
 * <h3>Interpolation</h3>
 *
 * <h4>Node values</h4> The
 * @ref GlossNodes "node values"
 * are moments on faces.
 *
 * <h4>Generalized support points</h4> To calculate the node values, we are
 * using a QGauss rule on each face. By default, we are using a two point rule
 * to integrate Rannacher-Turek functions exactly. But in order to be able to
 * interpolate other functions with sufficient accuracy, the number of
 * quadrature points used on a face can be adjusted in the constructor.
 *
 * @ingroup fe
 * @author Patrick Esser
 * @date 2015
 */
template <int dim>
class FE_RannacherTurek : public FE_Poly<PolynomialsRannacherTurek<dim>, dim>
{
public:
  /**
   * Constructor for Rannacher-Turek element of given @p order, using @p
   * n_face_support_points quadrature points on each face for interpolation.
   * Notice that the element of order 0 contains polynomials of degree 2.
   *
   * The element is currently only implemented for order 0 in 2D.
   */
  FE_RannacherTurek(const unsigned int order = 0,
                    const unsigned int n_face_support_points = 2);

  virtual std::string get_name() const;

  virtual
  std::unique_ptr<FiniteElement<dim,dim> >
  clone() const;

  // documentation inherited from the base class
  virtual
  void
  convert_generalized_support_point_values_to_nodal_values (const std::vector<Vector<double> > &support_point_values,
                                                            std::vector<double>                &nodal_values) const;

private:
  /**
   * Order of this element.
   */
  const unsigned int order;

  /**
   * The number of quadrature points used on each face to evaluate node
   * functionals during interpolation.
   */
  const unsigned int n_face_support_points;

  /**
   * The weights used on the faces to evaluate node functionals.
   */
  std::vector<double> weights;

  /**
   * Compute generalized support points and their weights.
   */
  void initialize_support_points();
  /**
   * Return information about degrees of freedom per object as needed during
   * construction.
   */
  std::vector<unsigned int> get_dpo_vector();
};


DEAL_II_NAMESPACE_CLOSE

#endif
